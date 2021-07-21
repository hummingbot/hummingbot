'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('drule', renderer, ['rule', 'cache']);
    }

    renderer.drule = function (styles, block) {
        var className = renderer.rule(styles, block);

        var closure = function (dynamicStyles) {
            if (!dynamicStyles) {
                return className;
            }

            var dynamicClassName = renderer.cache(dynamicStyles);

            return className + dynamicClassName;
        };

        closure.toString = function () {
            return className;
        };

        return closure;
    };
};
