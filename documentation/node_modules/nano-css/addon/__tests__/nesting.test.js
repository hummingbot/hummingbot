/* eslint-disable */
'use strict';

var env = require('./env');
var create = require('../../index').create;
var addonNesting = require('../../addon/nesting').addon;

function createNano (config) {
    var nano = create(config);

    addonNesting(nano);

    return nano;
};

describe('nesting', function () {
    it('installs without crashing', function () {
        var nano = createNano();
    });

    it('prepends selectors if no & operand', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.foo', {
            '.one,.two': {
                color: 'tomato'
            }
        });

        expect(nano.putRaw.mock.calls[0][0].includes('.foo .one,.foo .two')).toBe(true);
    });

    it('expands & operand after', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();

        nano.put('.one, #two', {
            '.foo &': {
                color: 'tomato'
            }
        });

        var result = nano.putRaw.mock.calls[0][0].replace(/ +(?= )/g,'');

        expect(result.includes('.foo .one,.foo #two')).toBe(true);
    });

    it('expands & operand before', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();
        nano.put('.foo', {
            '&:hover': {
                color: 'tomato'
            },
            '& .bar': {
                color: 'tomato'
            },
        });

        var css1 = nano.putRaw.mock.calls[0][0].replace(/ +(?= )/g,'');
        var css2 = nano.putRaw.mock.calls[1][0].replace(/ +(?= )/g,'');

        expect(css1.includes('.foo:hover')).toBe(true);
        expect(css2.includes('.foo .bar')).toBe(true);
    });

    it('expands multiple & operands', function () {
        var nano = createNano();

        nano.putRaw = jest.fn();
        nano.put('.foo', {
            '& + &': {
                color: 'tomato'
            },
        });

        var css1 = nano.putRaw.mock.calls[0][0].replace(/ +(?= )/g,'');

        expect(css1.includes('.foo + .foo')).toBe(true);
    });
});
