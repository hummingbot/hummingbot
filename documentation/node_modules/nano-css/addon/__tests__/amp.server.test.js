/** @jest-environment node */
/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;
var addonAmp = require('../../addon/amp').addon;
var isProd = process.env.NODE_ENV === 'production';

function createNano (config, addonConfig) {
    var nano = create(config);

    addonAmp(nano, addonConfig);

    return nano;
};

describe('amp', function () {
    it('is a function', function () {
        expect(typeof addonAmp).toBe('function');
    });

    it('allows inserting rules', function () {
        var nano = createNano();

        nano.put('.foo', {
            color: 'red'
        });

        nano.put('.bar', {
            color: 'red'
        });

        expect(nano.raw.replace(/[\s\n]+/g, '')).toBe('.foo{color:red;}.bar{color:red;}');
    });

    if (isProd) {
        it('caps at limit', function () {
            var nano = createNano({}, {
                limit: 40
            });
            
            nano.put('.foo', {
                color: 'red'
            });
            
            nano.put('.bar', {
                color: 'red'
            });
            
            nano.put('.baz', {
                color: 'red'
            });
            
            expect(nano.raw.replace(/[\s\n]+/g, '')).toBe('.foo{color:red;}.bar{color:red;}');
        });
    }

    it('warns on !important', function () {
        var nano = createNano();
        var console$error = console.error;
        var calls = [];

        console.error = function () {
            calls.push(arguments);
        };

        nano.put('.foo', {
            color: 'red'
        });

        expect(calls.length).toBe(0);

        nano.put('.bar', {
            color: 'blue !important'
        });

        expect(nano.raw.indexOf('!important') > -1).toBe(true);

        if (env.isDev) {
            expect(calls.length).toBe(1);
            expect(calls[0][0].indexOf('!important') > -1).toBe(true);
        } else {
            expect(calls.length).toBe(0);
        }

        console.error = console$error
    });

    it('removes !important', function () {
        var nano = createNano(null, {
            removeImportant: true
        });

        nano.put('.bar', {
            color: 'blue !important'
        });

        expect(nano.raw.indexOf('!important') > -1).toBe(false);
    });

    it('warns on reserved selectors', function () {
        var nano = createNano();
        var console$error = console.error;
        var calls = [];

        console.error = function () {
            calls.push(arguments);
        };

        nano.put('.foo', {
            color: 'red'
        });

        expect(calls.length).toBe(0);

        nano.put('.-amp-bar', {
            color: 'blue'
        });

        if (env.isDev) {
            expect(calls.length).toBe(1);
        } else {
            expect(calls.length).toBe(0);
        }

        nano.put('i-amp-baz', {
            color: 'yellow'
        });

        if (env.isDev) {
            expect(calls.length).toBe(2);
        } else {
            expect(calls.length).toBe(0);
        }

        nano.put('amp-baz', {
            color: 'green'
        });

        if (env.isDev) {
            expect(calls.length).toBe(2);
        } else {
            expect(calls.length).toBe(0);
        }

        console.error = console$error
    });

    it('removes reserved selectors', function () {
        var nano = createNano(null, {
            removeReserved: true
        });

        nano.put('.foo', {
            color: 'blue'
        });

        var length = nano.raw.length;

        nano.put('.-amp-bar', {
            color: 'red'
        });

        expect(nano.raw.length).toBe(length);

        nano.put('i-amp-baz', {
            color: 'green'
        });

        expect(nano.raw.length).toBe(length);

        nano.put('amp-bazooka', {
            color: 'orange'
        });

        expect(nano.raw.length > length).toBe(true);
    });

    it('warns on banned declarations', function () {
        var nano = createNano();
        var console$error = console.error;
        var calls = [];

        console.error = function () {
            calls.push(arguments);
        };

        nano.put('.foo', {
            color: 'red'
        });

        expect(calls.length).toBe(0);

        nano.put('.bar', {
            behavior: 'something'
        });

        if (env.isDev) {
            expect(calls.length).toBe(1);
        } else {
            expect(calls.length).toBe(0);
        }

        console.error = console$error
    });

    it('removes banned declarations', function () {
        var nano = createNano(null, {
            removeBanned: true
        });

        nano.put('.foo', {
            color: 'blue'
        });

        nano.put('.bar', {
            behavior: 'something'
        });

        expect(nano.raw.indexOf('behavior')).toBe(-1);
    });
});
