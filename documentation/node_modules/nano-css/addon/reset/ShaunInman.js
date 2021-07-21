'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        'body,div,dl,dt,dd,ul,ol,li,h1,h2,h3,h4,h5,h6,pre,form,fieldset,input,p,blockquote,table,th,td,embed,object': {
            pad: 0,
            mar: 0,
        },
        table: {
            'border-collapse': 'collapse',
            'border-spacing': 0,
        },
        'fieldset,img,abbr': {
            bd: 0,
        },
        'address,caption,cite,code,dfn,em,h1,h2,h3,h4,h5,h6,strong,th,var': {
            fw: 'normal',
            fs: 'normal',
        },
        ul: {
            'list-style': 'none',
        },
        'caption,th': {
            ta: 'left',
        },
        'h1,h2,h3,h4,h5,h6': {
            fz: '1.0em',
        },
        'q:before,q:after': {
            con: '""',
        },
        'a,ins': {
            td: 'none',
        },
    };

    renderer.put('', css);
};
