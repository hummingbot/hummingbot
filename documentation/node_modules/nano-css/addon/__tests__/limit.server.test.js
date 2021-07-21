/** @jest-environment node */
/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonLimit = require('../../addon/limit').addon;

function createNano (config) {
    var nano = create(config);

    addonLimit(nano);

    return nano;
};

describe('limit', function () {
    it('allows inserting rules', function () {
        var nano = create();

        nano.put('.foo', {
            color: 'red'
        });

        nano.put('.bar', {
            color: 'red'
        });

        nano.put('.baz', {
            color: 'red'
        });

        expect(nano.raw.replace(/[\s\n]+/g, '')).toBe('.foo{color:red;}.bar{color:red;}.baz{color:red;}');
    });

    it('caps at limit', function () {
        var nano = create();

        addonLimit(nano, 40);

        nano.put('.foo', {
            color: 'red'
        });

        nano.put('.bar', {
            color: 'red'
        });

        nano.put('.baz', {
            color: 'red'
        });
console.log(nano.raw);
        expect(nano.raw.replace(/[\s\n]+/g, '')).toBe('.foo{color:red;}.bar{color:red;}');
    });
});
