'use strict';

var addonCache = require('./cache').addon;

exports.addon = function (renderer) {
    if (!renderer.cache) {
        addonCache(renderer);
    }

    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('jsx', renderer, ['rule', 'cache']);
    }

    renderer.jsx = function (fn, styles, block) {
        var className;
        var isElement = typeof fn === 'string';

        // In dev mode emit CSS immediately so correct sourcemaps can be generated.
        if (process.env.NODE_ENV !== 'production') {
            className = renderer.rule(styles, block);
        }

        var Component = function (props) {
            if (!className) {
                className = renderer.rule(styles, block);
            }

            var copy = props;
            var $as = copy.$as;
            var $ref = copy.$ref;

            if (process.env.NODE_ENV !== 'production') {
                copy = renderer.assign({}, props);
            }

            var dynamicClassName = renderer.cache(props.css);
            delete copy.css;
            delete copy.$as;

            if (isElement || $as) {
                delete copy.$ref;
                copy.ref = $ref;
            }

            copy.className = (props.className || '') + className + dynamicClassName;

            return (isElement || $as)
                ? renderer.h($as || fn, copy)
                : fn(copy);
        };

        if (process.env.NODE_ENV !== 'production') {
            if (block) {
                Component.displayName = 'jsx(' + block + ')';
            }
        }

        return Component;
    };
};
