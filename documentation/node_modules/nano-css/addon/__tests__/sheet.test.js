/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonSheet = require('../../addon/sheet').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);
    addonSheet(nano);

    return nano;
};

describe('sheet()', function () {
    it('installs sheet() method', function () {
        var nano = create();

        expect(typeof nano.sheet).toBe('undefined');

        addonRule(nano);
        addonSheet(nano);

        expect(typeof nano.sheet).toBe('function');
    });

    it('returns a styles object', function () {
        var nano = createNano();
        var styles = nano.sheet({
            input: {
                color: 'red',
            },
            button: {
                color: 'blue'
            }
        });

        expect(typeof styles.input).toBe('string');
        expect(typeof styles.button).toBe('string');
    });

    it('inserts a rule only when first accessed', function () {
        var nano = createNano();

        nano.rule = jest.fn();

        var styles = nano.sheet({
            input: {
                color: 'red',
            },
            button: {
                color: 'blue'
            }
        });

        expect(nano.rule).toHaveBeenCalledTimes(0);

        styles.input;

        expect(nano.rule).toHaveBeenCalledTimes(1);

        styles.button;

        expect(nano.rule).toHaveBeenCalledTimes(2);

        expect(nano.rule.mock.calls[0][0]).toEqual({color: 'red'});
        expect(nano.rule.mock.calls[1][0]).toEqual({color: 'blue'});

        expect(typeof nano.rule.mock.calls[0][1]).toBe('string');
        expect(typeof nano.rule.mock.calls[1][1]).toBe('string');
    });
});
