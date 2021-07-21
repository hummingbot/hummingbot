/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);

    return nano;
};

describe('rule()', function () {
    it('installs rule() method', function () {
        var nano = create();

        expect(typeof nano.rule).toBe('undefined');

        addonRule(nano);

        expect(typeof nano.rule).toBe('function');
    });

    it('puts CSS styles', function () {
        var nano = createNano({
            pfx: 'test-'
        });

        nano.put = jest.fn();

        var classNames = nano.rule({
            color: 'red'
        }, 'foobar');

        expect(nano.put).toHaveBeenCalledTimes(1);
        expect(nano.put).toHaveBeenCalledWith('.test-foobar', {color: 'red'});
        expect(classNames).toBe(' test-foobar');
    });

    it('generates class name automatically if not specified', function () {
        var nano = createNano({
            pfx: 'test-'
        });

        nano.put = jest.fn();

        var css = {color: 'red'};
        var classNames = nano.rule(css);
        var computed = 'test-' + nano.hash(css);

        expect(nano.put).toHaveBeenCalledTimes(1);
        expect(nano.put).toHaveBeenCalledWith('.' + computed, css);
        expect(classNames).toBe(' ' + computed);
    });
});
