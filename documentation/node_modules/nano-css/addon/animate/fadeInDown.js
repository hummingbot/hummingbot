'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('animate', renderer, ['keyframes']);
    }

    renderer.put('', {
        '@keyframes fadeInDown': {
            from: {
                opacity: 0,
                transform: 'translate3d(0, -10%, 0)'
            },

            to: {
                opacity: 1,
                transform: 'translate3d(0, 0, 0)',
            }
        },

        '.fadeInDown': {
            animation: 'fadeInDown .3s',
        }
    });
};
