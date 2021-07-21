/* сжимаем код через htmlMinify */

'use strict';

const assert = require('assert');
const Minifier = require('html-minifier');

const Options = {
    removeComments:                 true,
    removeCommentsFromCDATA:        true,
    removeCDATASectionsFromCDATA:   true,
    collapseWhitespace:             true,
    collapseBooleanAttributes:      true,
    removeAttributeQuotes:          true,
    removeRedundantAttributes:      true,
    useShortDoctype:                true,
    removeEmptyAttributes:          true,
    /* оставляем, поскольку у нас
     * в элемент fm генерируеться
     * таблица файлов
     */
    removeEmptyElements:            false,
    removeOptionalTags:             true,
    removeScriptTypeAttributes:     true,
    removeStyleLinkTypeAttributes:  true,
    
    minifyJS:                       true,
    minifyCSS:                      true,
};

/**
 * minify html data.
 *
 * @param data
 * @param callback
 */
module.exports = (data) => {
    assert(data);
    
    return Minifier.minify(data, Options);
};

