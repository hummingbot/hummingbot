"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
var quoted_1 = __importDefault(require("../tree/quoted"));
var anonymous_1 = __importDefault(require("../tree/anonymous"));
var javascript_1 = __importDefault(require("../tree/javascript"));
exports.default = {
    e: function (str) {
        return new quoted_1.default('"', str instanceof javascript_1.default ? str.evaluated : str.value, true);
    },
    escape: function (str) {
        return new anonymous_1.default(encodeURI(str.value).replace(/=/g, '%3D').replace(/:/g, '%3A').replace(/#/g, '%23').replace(/;/g, '%3B')
            .replace(/\(/g, '%28').replace(/\)/g, '%29'));
    },
    replace: function (string, pattern, replacement, flags) {
        var result = string.value;
        replacement = (replacement.type === 'Quoted') ?
            replacement.value : replacement.toCSS();
        result = result.replace(new RegExp(pattern.value, flags ? flags.value : ''), replacement);
        return new quoted_1.default(string.quote || '', result, string.escaped);
    },
    '%': function (string /* arg, arg, ... */) {
        var args = Array.prototype.slice.call(arguments, 1);
        var result = string.value;
        var _loop_1 = function (i) {
            /* jshint loopfunc:true */
            result = result.replace(/%[sda]/i, function (token) {
                var value = ((args[i].type === 'Quoted') &&
                    token.match(/s/i)) ? args[i].value : args[i].toCSS();
                return token.match(/[A-Z]$/) ? encodeURIComponent(value) : value;
            });
        };
        for (var i = 0; i < args.length; i++) {
            _loop_1(i);
        }
        result = result.replace(/%%/g, '%');
        return new quoted_1.default(string.quote || '', result, string.escaped);
    }
};
//# sourceMappingURL=string.js.map