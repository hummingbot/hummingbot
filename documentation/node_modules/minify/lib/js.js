'use strict';

const terser = require('terser');
const assert = require('assert');

/**
 * minify js data.
 *
 * @param data
 */
module.exports = (data) => {
    assert(data);
    
    const {
        error,
        code,
    } = terser.minify(data);
    
    if (error)
        throw error;
    
    return code;
};

