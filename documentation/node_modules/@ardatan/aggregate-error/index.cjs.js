'use strict';

const tslib = require('tslib');

var cleanInternalStack = function (stack) { return stack.replace(/\s+at .*aggregate-error\/index.js:\d+:\d+\)?/g, ''); };

/**
Escape RegExp special characters.
You can also use this to escape a string that is inserted into the middle of a regex, for example, into a character class.
@example
```
import escapeStringRegexp = require('escape-string-regexp');
const escapedString = escapeStringRegexp('How much $ for a 🦄?');
//=> 'How much \\$ for a 🦄\\?'
new RegExp(escapedString);
```
*/
var escapeStringRegexp = function (string) {
    if (typeof string !== 'string') {
        throw new TypeError('Expected a string');
    }
    // Escape characters with special meaning either inside or outside character sets.
    // Use a simple backslash escape when it’s always valid, and a `\xnn` escape when the simpler form would be disallowed by Unicode patterns’ stricter grammar.
    return string
        .replace(/[|\\{}()[\]^$+*?.]/g, '\\$&')
        .replace(/-/g, '\\x2d');
};

var extractPathRegex = /\s+at.*[(\s](.*)\)?/;
var pathRegex = /^(?:(?:(?:node|(?:internal\/[\w/]*|.*node_modules\/(?:babel-polyfill|pirates)\/.*)?\w+)\.js:\d+:\d+)|native)/;
/**
Clean up error stack traces. Removes the mostly unhelpful internal Node.js entries.
@param stack - The `stack` property of an `Error`.
@example
```
import cleanStack = require('clean-stack');
const error = new Error('Missing unicorn');
console.log(error.stack);
// Error: Missing unicorn
//     at Object.<anonymous> (/Users/sindresorhus/dev/clean-stack/unicorn.js:2:15)
//     at Module._compile (module.js:409:26)
//     at Object.Module._extensions..js (module.js:416:10)
//     at Module.load (module.js:343:32)
//     at Function.Module._load (module.js:300:12)
//     at Function.Module.runMain (module.js:441:10)
//     at startup (node.js:139:18)
console.log(cleanStack(error.stack));
// Error: Missing unicorn
//     at Object.<anonymous> (/Users/sindresorhus/dev/clean-stack/unicorn.js:2:15)
```
*/
var cleanStack = function (stack, basePath) {
    var basePathRegex = basePath && new RegExp("(at | \\()" + escapeStringRegexp(basePath), 'g');
    return stack.replace(/\\/g, '/')
        .split('\n')
        .filter(function (line) {
        var pathMatches = line.match(extractPathRegex);
        if (pathMatches === null || !pathMatches[1]) {
            return true;
        }
        var match = pathMatches[1];
        // Electron
        if (match.includes('.app/Contents/Resources/electron.asar') ||
            match.includes('.app/Contents/Resources/default_app.asar')) {
            return false;
        }
        return !pathRegex.test(match);
    })
        .filter(function (line) { return line.trim() !== ''; })
        .map(function (line) {
        if (basePathRegex) {
            line = line.replace(basePathRegex, '$1');
        }
        return line;
    })
        .join('\n');
};

/**
Indent each line in a string.
@param string - The string to indent.
@param count - How many times you want `options.indent` repeated. Default: `1`.
@example
```
import indentString = require('indent-string');
indentString('Unicorns\nRainbows', 4);
//=> '    Unicorns\n    Rainbows'
indentString('Unicorns\nRainbows', 4, {indent: '♥'});
//=> '♥♥♥♥Unicorns\n♥♥♥♥Rainbows'
```
*/
var indentString = function (string, count, options) {
    if (count === void 0) { count = 1; }
    options = Object.assign({
        indent: ' ',
        includeEmptyLines: false,
    }, options);
    if (typeof string !== 'string') {
        throw new TypeError("Expected `input` to be a `string`, got `" + typeof string + "`");
    }
    if (typeof count !== 'number') {
        throw new TypeError("Expected `count` to be a `number`, got `" + typeof count + "`");
    }
    if (count < 0) {
        throw new RangeError("Expected `count` to be at least 0, got `" + count + "`");
    }
    if (typeof options.indent !== 'string') {
        throw new TypeError("Expected `options.indent` to be a `string`, got `" + typeof options.indent + "`");
    }
    if (count === 0) {
        return string;
    }
    var regex = options.includeEmptyLines ? /^/gm : /^(?!\s*$)/gm;
    return string.replace(regex, options.indent.repeat(count));
};

var AggregateError = /** @class */ (function (_super) {
    tslib.__extends(AggregateError, _super);
    function AggregateError(errors) {
        var _this = this;
        if (!Array.isArray(errors)) {
            throw new TypeError("Expected input to be an Array, got " + typeof errors);
        }
        var normalizedErrors = errors.map(function (error) {
            if (error instanceof Error) {
                return error;
            }
            if (error !== null && typeof error === 'object') {
                // Handle plain error objects with message property and/or possibly other metadata
                return Object.assign(new Error(error.message), error);
            }
            return new Error(error);
        });
        var message = normalizedErrors
            .map(function (error) {
            // The `stack` property is not standardized, so we can't assume it exists
            return typeof error.stack === 'string' ? cleanInternalStack(cleanStack(error.stack)) : String(error);
        })
            .join('\n');
        message = '\n' + indentString(message, 4);
        _this = _super.call(this, message) || this;
        _this.name = 'AggregateError';
        Object.defineProperty(_this, Symbol.iterator, {
            get: function () { return function () { return normalizedErrors[Symbol.iterator](); }; },
        });
        return _this;
    }
    return AggregateError;
}(Error));

module.exports = AggregateError;
//# sourceMappingURL=index.cjs.js.map
