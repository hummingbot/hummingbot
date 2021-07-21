/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;
var addonKeyframes = require('../../addon/keyframes').addon;

function createNano (config) {
    var nano = create(config);

    addonKeyframes(nano);

    return nano;
};

describe('keyframes', function () {
    it('installs interface', function () {
        var nano = createNano();

        expect(typeof nano.keyframes).toBe('function');
    });

    it('creates keyframe style sheet on client', function () {
        var nano = createNano();

        if (env.isClient) {
            expect(typeof nano.ksh).toBe('object');
        } else {
            expect(typeof nano.ksh).toBe('undefined');
        }
    });

    describe('keyframes()', function () {
        it('returns animation name', function () {
            var nano = createNano();
            var name = nano.keyframes({
                to: {
                    transform: 'rotate(360deg)'
                }
            });

            expect(typeof name).toBe('string');
            expect(name.length > 0).toBe(true);
        });

        it('puts animation CSS', function () {
            var nano = create();

            addonKeyframes(nano, {
                prefixes: ['']
            });

            nano.putRaw = jest.fn();
            nano.ksh = {
                appendChild: jest.fn()
            };

            var name = nano.keyframes({
                to: {
                    transform: 'rotate(360deg)'
                }
            });

            if (env.isClient) {
                expect(nano.ksh.appendChild).toHaveBeenCalledTimes(1);
            } else {
                expect(nano.putRaw).toHaveBeenCalledTimes(1);
            }
        });

        it('puts animation CSS with all prefixes', function () {
            var nano = create();

            addonKeyframes(nano, {
                prefixes: ['-webkit-', '-moz-', '']
            });

            nano.putRaw = jest.fn();
            nano.ksh = {
                appendChild: jest.fn()
            };

            var name = nano.keyframes({
                to: {
                    transform: 'rotate(360deg)'
                }
            });

            if (env.isClient) {
                expect(nano.ksh.appendChild).toHaveBeenCalledTimes(3);
            } else {
                expect(nano.putRaw).toHaveBeenCalledTimes(3);
                expect(nano.putRaw.mock.calls[0][0].includes('to{transform:rotate(360deg);}')).toBe(true);
                expect(nano.putRaw.mock.calls[1][0].includes('to{transform:rotate(360deg);}')).toBe(true);
                expect(nano.putRaw.mock.calls[2][0].includes('to{transform:rotate(360deg);}')).toBe(true);
            }
        });
    });

    describe('CSS-like object', function () {
        it('puts animation CSS with all prefixes', function () {
            var nano = create();

            addonKeyframes(nano, {
                prefixes: ['-webkit-', '-moz-', '']
            });

            nano.putRaw = jest.fn();
            nano.ksh = {
                appendChild: jest.fn()
            };

            nano.put('', {
                '@keyframes': {
                    to: {
                        transform: 'rotate(360deg)'
                    }
                }
            });

            if (env.isClient) {
                expect(nano.ksh.appendChild).toHaveBeenCalledTimes(3);
            } else {
                expect(nano.putRaw).toHaveBeenCalledTimes(3);
                expect(nano.putRaw.mock.calls[0][0].includes('to{transform:rotate(360deg);}')).toBe(true);
                expect(nano.putRaw.mock.calls[1][0].includes('to{transform:rotate(360deg);}')).toBe(true);
                expect(nano.putRaw.mock.calls[2][0].includes('to{transform:rotate(360deg);}')).toBe(true);
            }
        });
    });
});
