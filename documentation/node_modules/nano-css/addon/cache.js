'use strict';

exports.addon = function (renderer) {
    var cache = {};

    renderer.cache = function (css) {
        if (!css) return '';

        var key = renderer.hash(css);

        if (!cache[key]) {
            cache[key] = renderer.rule(css, key);
        }

        return cache[key];
    };
};
