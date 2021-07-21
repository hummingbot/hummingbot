'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('animate', renderer, ['keyframes']);
    }

    renderer.put('', {
        '@keyframes fadeOutScale': {
            to: {
                opacity: 0,
                transform: 'scale(.95)',
            }
        },

        '.fadeOutScale': {
            animation: 'fadeOutScale .3s linear',
            'animation-fill-mode': 'forwards',
        }
    });
};
