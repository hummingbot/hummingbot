/** @jest-environment node */
'use strict';

process.env.NODE_ENV = 'development';

var create = require('../../index').create;
var addon = require('../../addon/cssom').addon;

test('should load without crashing', () => {
    var nano = create();
    addon(nano);
});
