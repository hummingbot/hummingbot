/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonAtoms = require('../../addon/atoms').addon;

function createNano (config) {
    var nano = create(config);

    addonAtoms(nano);

    return nano;
};

describe('atoms', function () {
    it('installs without crashing', function () {
        var nano = createNano();
    });

    it('passes through standard properties', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.foo', {
            color: 'red'
        });

        expect(nano.putRaw.mock.calls[0][0].includes('color:red')).toBe(true);
    });

    it('expands atoms', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.bar', {
            col: 'blue',
            ta: 'center',
            minH: '100px',
            maxH: '200px'
        });

        expect(nano.putRaw.mock.calls[0][0].includes('color:blue')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('text-align:center')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('min-height:100px')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('max-height:200px')).toBe(true);
    });
});
