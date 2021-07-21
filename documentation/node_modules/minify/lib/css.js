/* сжимаем код через clean-css */

'use strict';

const assert = require('assert');
const Clean = require('clean-css');

/**
 * minify css data.
 *
 * @param data
 */
module.exports = (data) => {
    assert(data);
    
    const {
        styles,
        errors,
    } = new Clean().minify(data);
    
    const [error] = errors;
    
    if (error)
        throw error;
    
    return styles;
};

