'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        '*': {
            'vertical-align': 'baseline',
            fw: 'inherit',
            ff: 'inherit',
            fs: 'inherit',
            fz: '100%',
            bd: '0 none',
            out: 0,
            pad: 0,
            mar: 0,
        },
    };

    renderer.put('', css);
};
