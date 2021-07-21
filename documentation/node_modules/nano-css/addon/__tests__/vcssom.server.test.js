/** @jest-environment node */
'use strict';

process.env.NODE_ENV = 'development';

var create = require('../../index').create;
var addonCSSOM = require('../../addon/cssom').addon;
var addonVCSSOM = require('../../addon/vcssom').addon;

test('should load without crashing', () => {
    var nano = create();
    addonCSSOM(nano);
    addonVCSSOM(nano);
});
