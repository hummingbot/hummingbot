'use strict';

var Stylis = require('stylis');
var onRulePlugin = require('./stylis/plugin-onRule');

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('stylis', renderer, ['put']);
    }

    renderer.stylis = new Stylis();

    var plugin = onRulePlugin(function (rawCssRule) {
        renderer.putRaw(rawCssRule);
    });

    renderer.stylis.use(plugin);

    var put = renderer.put;

    renderer.put = function (selector, css) {
        if (typeof css !== 'string') {
            return put(selector, css);
        }

        renderer.stylis(selector, css);
    };
};
