'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        '*': {
            'vertical-align': 'baseline',
            ff: 'inherit',
            fs: 'inherit',
            fz: '100%',
            bd: 'none',
            pad: 0,
            mar: 0,
        },
        body: {
            pad: '5px',
        },
        'h1, h2, h3, h4, h5, h6, p, pre, blockquote, form, ul, ol, dl': {
            mar: '20px 0',
        },
        'li, dd, blockquote': {
            marl: '40px',
        },
        table: {
            'border-collapse': 'collapse',
            'border-spacing': 0,
        },
    };

    renderer.put('', css);
};
