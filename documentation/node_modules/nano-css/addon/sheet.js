'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('sheet', renderer, ['rule']);
    }

    renderer.sheet = function (map, block) {
        var result = {};

        if (!block) {
            block = renderer.hash(map);
        }

        var onElementModifier = function (elementModifier) {
            var styles = map[elementModifier];

            if ((process.env.NODE_ENV !== 'production') && renderer.sourcemaps) {
                // In dev mode emit CSS immediately to generate sourcemaps.
                result[elementModifier] = renderer.rule(styles, block + '-' + elementModifier);
            } else {
                Object.defineProperty(result, elementModifier, {
                    configurable: true,
                    enumerable: true,
                    get: function () {
                        var classNames = renderer.rule(styles, block + '-' + elementModifier);

                        Object.defineProperty(result, elementModifier, {
                            value: classNames,
                            enumerable: true
                        });

                        return classNames;
                    },
                });
            }
        };

        for (var elementModifier in map) {
            onElementModifier(elementModifier);
        }

        return result;
    };
};
