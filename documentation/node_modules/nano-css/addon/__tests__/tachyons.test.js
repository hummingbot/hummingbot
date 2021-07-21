/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonCache = require('../../addon/cache').addon;
var addonTachyons = require('../../addon/tachyons').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);
    addonCache(nano);
    addonTachyons(nano);

    return nano;
};

describe('tachyons', function () {
    it('works', function () {
        var nano = createNano();

        expect(nano.s.f1.obj).toEqual({
            fontSize: '3rem'
        });
    });

    it('multiple rules', function () {
        var nano = createNano();

        expect(nano.s.f4.i.b.strike.ttu.serif.measure.fl.wTwoThirds.obj).toMatchSnapshot();
    });

    it('.grow', function () {
        var nano = createNano();

        expect(nano.s.grow.obj).toMatchSnapshot();
    });

    it('.dim', function () {
        var nano = createNano();

        expect(nano.s.dim.obj).toMatchSnapshot();
    });
});
