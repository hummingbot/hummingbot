'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('../__dev__/warnOnMissingDependencies')('reset', renderer, ['put']);
    }

    var css = {
        '*': {
            td: 'none',
            fz: '1em',
            out: 'none',
            pad: 0,
            mar: 0,
        },
        'code,kbd,samp,pre,tt,var,textarea,input,select,isindex,listing,xmp,plaintext': {
            'white-space': 'normal',
            fz: '1em',
            font: 'inherit',
        },
        'dfn,i,cite,var,address,em': {
            fs: 'normal',
        },
        'th,b,strong,h1,h2,h3,h4,h5,h6': {
            fw: 'normal',
        },
        'a,img,a img,iframe,form,fieldset,abbr,acronym,object,applet,table': {
            bd: 'none',
        },
        table: {
            'border-collapse': 'collapse',
            'border-spacing': 0,
        },
        'caption,th,td,center': {
            'vertical-align': 'top',
            ta: 'left',
        },
        body: {
            bg: 'white',
            lh: 1,
            col: 'black',
        },
        q: {
            quotes: '"" ""',
        },
        'ul,ol,dir,menu': {
            'list-style': 'none',
        },
        'sub,sup': {
            'vertical-align': 'baseline',
        },
        a: {
            col: 'inherit',
        },
        hr: {
            d: 'none',
        },
        font: {
            col: 'inherit !important',
            font: 'inherit !important',
        },
        marquee: {
            ov: 'inherit !important',
            '-moz-binding': 'none',
        },
        blink: {
            td: 'none',
        },
        nobr: {
            'white-space': 'normal',
        },
    };

    renderer.put('', css);
};
