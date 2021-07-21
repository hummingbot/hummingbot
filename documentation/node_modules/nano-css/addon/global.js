'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('global', renderer, ['put']);
    }

    var selector = renderer.selector;

    renderer.selector = function (parent, current) {
        if (parent.indexOf(':global') > -1) parent = '';

        return selector(parent, current);
    };

    renderer.global = function (css) {
        return renderer.put('', css);
    };
};
