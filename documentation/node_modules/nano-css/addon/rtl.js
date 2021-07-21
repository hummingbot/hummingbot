'use strict';

var rtl = require('rtl-css-js').default;

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('rtl', renderer, ['put']);
    }

    var put = renderer.put;

    renderer.put = function (selector, css) {
        return put(selector, rtl(css));
    };
};
