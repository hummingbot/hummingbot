'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('rule', renderer, ['put']);
    }

    var blocks;

    if (process.env.NODE_ENV !== 'production') {
        blocks = {};
    }

    renderer.rule = function (css, block) {
        // Warn user if CSS selectors clash.
        if (process.env.NODE_ENV !== 'production') {
            if (block) {
                if (typeof block !== 'string') {
                    throw new TypeError(
                        'nano-css block name must be a string. ' +
                        'For example, use nano.rule({color: "red", "RedText").'
                    );
                }

                if (blocks[block]) {
                    console.error('Block name "' + block + '" used more than once.');
                }

                blocks[block] = 1;
            }
        }

        block = block || renderer.hash(css);
        block = renderer.pfx + block;
        renderer.put('.' + block, css);

        return ' ' + block;
    };
};
