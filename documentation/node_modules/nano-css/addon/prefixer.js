'use strict';

var prefixAll = require('inline-style-prefixer/static');

var CAMEL_REGEX = /-[a-z\u00E0-\u00F6\u00F8-\u00FE]/g;

var matchCallback = function (match) {
    return match.slice(1).toUpperCase();
};

exports.addon = function (renderer) {
    var decl = renderer.decl;
    var origPut = renderer.put;

    renderer.camel = function (prop) {
        return prop.replace(CAMEL_REGEX, matchCallback);
    };

    renderer.prefix = function (prop, value) {
        var obj = {};
        obj[renderer.camel(prop)] = value;
        obj = prefixAll(obj);

        var result = {};

        for (var propPrefixed in obj) {
            value = obj[propPrefixed];
            if (propPrefixed.slice(0, 2) === 'ms') {
                propPrefixed = 'M' + propPrefixed.slice(1);
            }
            propPrefixed = renderer.kebab(propPrefixed);

            if (value instanceof Array) {
                result[propPrefixed] = value.join(';' + propPrefixed + ':');
            } else {
                result[propPrefixed] = value;
            }
        }

        return result;
    };

    renderer.decl = function (prop, value) {
        var result = renderer.prefix(prop, value);

        var returned = '';
        Object.keys(result).forEach(function (key) {
            var str = decl(key, value);
            returned += str;
        });

        return returned;
    };

    function newPut(selector, decls, atrule) {
        var indexed = selector.indexOf('::placeholder');
        if (indexed > -1) {
            var split = selector.split(',');
            if (split.length > 1) {
                split.forEach(function(sp) {
                    newPut(sp.trim(), decls, atrule);
                });
                return;
            }
            var bareSelect = selector.substring(0, indexed);
            [
                '::-webkit-input-placeholder',
                '::-moz-placeholder',
                ':-ms-input-placeholder',
                ':-moz-placeholder'
            ].forEach(function(ph) {
                origPut(bareSelect + ph, decls, atrule);
            });
        }
        origPut(selector, decls, atrule);
    }

    renderer.put = newPut;
};
