'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('animate', renderer, ['keyframes']);
    }

    renderer.put('', {
        '@keyframes fadeOut': {
            from: {
                opacity: 1,
            },
            to: {
                opacity: 0,
            }
        },

        '.fadeOut': {
            animation: 'fadeOut .3s linear',
            'animation-fill-mode': 'forwards',
        }
    });
};
