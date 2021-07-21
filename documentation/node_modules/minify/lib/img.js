'use strict';

const path = require('path');
const assert = require('assert');
const {promisify} = require('util');

const fromString = promisify(require('css-b64-images').fromString);

const ONE_KB = 2 ** 10;

const maxSize = 100 * ONE_KB;

/**
 * minify css data.
 * if can not minify return data
 *
 * @param name
 * @param data
 */
module.exports = async (name, data) => {
    const dir = path.dirname(name);
    const dirRelative = dir + '/../';
    
    assert(name);
    assert(data);
    
    return fromString(data, dir, dirRelative, {
        maxSize,
    });
};

