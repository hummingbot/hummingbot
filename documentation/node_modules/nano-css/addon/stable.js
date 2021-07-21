'use strict';

var stringify = require('fastest-stable-stringify');

exports.addon = function (renderer) {
    renderer.stringify = stringify;
};
