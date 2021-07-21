/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonCache = require('../../addon/cache').addon;
var addonJsx = require('../../addon/jsx').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);
    addonCache(nano);
    addonJsx(nano);

    return nano;
};

describe('jsx()', function () {
    it('installs interface', function () {
        var nano = createNano();

        expect(typeof nano.jsx).toBe('function');
    });

    it('creates a styling block', function () {
        var nano = createNano();
        var Comp = nano.jsx('button', {color: 'red'});

        expect(typeof Comp).toBe('function');
    });
});
