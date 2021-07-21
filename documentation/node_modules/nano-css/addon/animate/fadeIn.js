'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('animate', renderer, ['keyframes']);
    }

    renderer.put('', {
        '@keyframes fadeIn': {
            from: {
                opacity: 0,
            },
            to: {
                opacity: 1,
            }
        },

        '.fadeIn': {
            animation: 'fadeIn .4s linear',
        }
    });
};
