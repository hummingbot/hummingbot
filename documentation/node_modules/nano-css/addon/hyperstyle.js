'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('hyperstyle', renderer, ['sheet']);
    }

    renderer.hyperstyle = function (map, block) {
        var styles = renderer.sheet(map, block);

        return function (type, props) {
            if (props) {
                var styleName = props.styleName;

                if (styleName) {
                    var className = styles[styleName];

                    if (className) {
                        props.className = (props.className || '') + className;
                    }
                }
            }

            return renderer.h.apply(null, arguments);
        };
    };
};
