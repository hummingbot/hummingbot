/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonUnits = require('../../addon/units').addon;

function createNano (config) {
    var nano = create(config);

    addonUnits(nano);

    return nano;
};

describe('units', function () {
    it('creates public methods', function () {
        var nano = createNano();

        expect(typeof nano.px).toBe('function');
        expect(typeof nano.units).toBe('object');
        expect(typeof nano.units.px).toBe('function');
    });

    it('works', function () {
        var nano = createNano();

        expect(nano.px(25)).toBe('25px');
        expect(nano.units.px(25)).toBe('25px');
        expect(nano.units.pt(1)).toBe('1pt');
        expect(nano.pt(1)).toBe('1pt');
        expect(nano.vmax(100)).toBe('100vmax');
        expect(nano.vw(3)).toBe('3vw');
    });

    it('special cases', function () {
        var nano = createNano();

        expect(nano.pct(20)).toBe('20%');
        expect(nano.inch(3)).toBe('3in');
    });
});
