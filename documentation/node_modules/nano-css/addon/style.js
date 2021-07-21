'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('style', renderer, ['jsx']);
    }

    renderer.style = function (fn, styles, dynamicTemplate, block) {
        var jsxComponent = renderer.jsx(fn, styles, block);

        var Component = function(props) {
            var copy = props;

            if (process.env.NODE_ENV !== 'production') {
                copy = Object.assign({}, props);
            }

            if (dynamicTemplate) {
                copy.css = dynamicTemplate(props);
            }

            return jsxComponent(copy);
        };

        if (process.env.NODE_ENV !== 'production') {
            if (block || (typeof fn === 'function')) {
                Component.displayName = 'style(' + (block || fn.displayName || fn.name) + ')';
            }
        }

        return Component;
    };
};
