'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        'body,div,dl,dt,dd,ul,ol,li,h1,h2,h3,h4,h5,h6,pre,form,fieldset,input,textarea,p,blockquote,th,td': {
            pad: 0,
            mar: 0,
        },
        'fieldset, img': {
            bd: 0,
        },
        table: {
            'border-collapse': 'collapse',
            'border-spacing': 0,
        },
        'ol, ul': {
            'list-style': 'none',
        },
        'address, caption, cite, code, dfn, em, strong, th, var': {
            fw: 'normal',
            fs: 'normal',
        },
        'caption, th': {
            ta: 'left',
        },
        'h1, h2, h3, h4, h5, h6': {
            fw: 'normal',
            fs: '100%',
        },
        'q:before, q:after': {
            con: "''",
        },
        'abbr, acronym': {
            bd: 0,
        },
    };

    renderer.put('', css);
};

