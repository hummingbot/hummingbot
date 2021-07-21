/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;

describe('put()', function () {
    it('exits', function () {
        var nano = create();

        expect(typeof nano.put).toBe('function');
    });

    it('injects CSS using putRaw()', function () {
        var nano = create();

        nano.putRaw = jest.fn();
        nano.put('.foo', {
            color: 'tomato'
        });

        expect(nano.putRaw).toHaveBeenCalledTimes(1);
        expect(nano.putRaw.mock.calls[0][0].includes('.foo')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('color')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('tomato')).toBe(true);
    });

    it('first injects simple keys, before nested styles', function () {
        var nano = create();

        nano.putRaw = jest.fn();
        nano.put('.foo', {
            '.bar': {
                color: 'blue',
            },
            color: 'tomato',
        });

        expect(nano.putRaw).toHaveBeenCalledTimes(2);

        expect(nano.putRaw.mock.calls[0][0].includes('.foo')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('color')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('tomato')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('blue')).not.toBe(true);

        expect(nano.putRaw.mock.calls[1][0].includes('.bar')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('color')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('blue')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('tomato')).not.toBe(true);
    });

    it('first injects simple keys, before @media queries', function () {
        var nano = create();

        nano.putRaw = jest.fn();
        nano.put('.foo', {
            '@media (screen)': {
                color: 'blue',
            },
            color: 'tomato',
        });

        expect(nano.putRaw).toHaveBeenCalledTimes(2);

        expect(nano.putRaw.mock.calls[0][0].includes('.foo')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('color')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('tomato')).toBe(true);
        expect(nano.putRaw.mock.calls[0][0].includes('blue')).not.toBe(true);

        expect(nano.putRaw.mock.calls[1][0].includes('.foo')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('color')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('blue')).toBe(true);
        expect(nano.putRaw.mock.calls[1][0].includes('tomato')).not.toBe(true);
    });
});
