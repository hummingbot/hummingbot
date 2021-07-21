'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        'html, body': {
            pad: 0,
            mar: 0,
        },
        html: {
            fz: '1em',
        },
        body: {
            fz: '100%',
        },
        'a img, :link img, :visited img': {
            bd: 0,
        },
    };

    renderer.put('', css);
};
