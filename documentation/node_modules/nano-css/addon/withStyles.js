'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('withStyles', renderer, ['sheet']);
    }

    renderer.withStyles = function (map, fn, block) {
        block = block || fn.displayName || fn.name;

        var styles = renderer.sheet(map, block);
        var Component = function (props) {
            if (process.env.NODE_ENV !== 'production') {
                return fn(Object.assign({}, props, {
                    styles: styles
                }));
            }

            props.styles = styles;

            return fn(props);
        };

        if (process.env.NODE_ENV !== 'production') {
            if (block) {
                Component.displayName = 'withStyles(' + block + ')';
            }
        }

        return Component;
    };
};
