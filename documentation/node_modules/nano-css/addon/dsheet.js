'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('dsheet', renderer, ['sheet', 'cache']);
    }

    renderer.dsheet = function (map, block) {
        var styles = renderer.sheet(map, block);
        var closures = {};

        var createClosure = function (elementModifier) {
            var closure = function (dynamicStyles) {
                if (!dynamicStyles) {
                    return styles[elementModifier];
                }

                var dynamicClassName = renderer.cache(dynamicStyles);

                return styles[elementModifier] + dynamicClassName;
            };

            closure.toString = function () {
                return styles[elementModifier];
            };

            return closure;
        };

        for (var elementModifier in map) {
            closures[elementModifier] = createClosure(elementModifier);
        }

        return closures;
    };
};
