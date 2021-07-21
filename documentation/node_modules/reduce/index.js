'use strict';

var objectKeys = require('object-keys');

module.exports = function reduce(list, iterator) {
    var keys = objectKeys(list);
    var i = 0;
    var accumulator = list[0];
    var context = this;

    if (arguments.length === 2) {
        i = 1;
    } else if (arguments.length === 3) {
        accumulator = arguments[2];
    } else if (arguments.length >= 4) {
        context = arguments[2];
        accumulator = arguments[3];
    }

    for (var len = keys.length; i < len; i++) {
        var key = keys[i];
        var value = list[key];

        accumulator = iterator.call(context, accumulator, value, key, list);
    }

    return accumulator;
};
