'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        '*': {
            pad: 0,
            mar: 0,
        },
    };

    renderer.put('', css);
};
