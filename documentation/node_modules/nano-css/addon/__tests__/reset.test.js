/* eslint-disable */
'use strict';

var create = require('../../index').create;

var resets = [
    'EricMeyer',
    'EricMeyerCondensed',
    'Minimalistic',
    'Minimalistic2',
    'Minimalistic3',
    'PoorMan',
    'ShaunInman',
    'Siolon',
    'Tantek',
    'Tripoli',
    'Universal',
    'Yahoo',
    'Normalize',
];

describe('reset', function () {
    resets.forEach(function (name) {
        var addon = require('../../addon/reset/' + name).addon;

        it(name, function () {
            var nano = create();

            nano.put = jest.fn();

            addon(nano);

            expect(nano.put).toHaveBeenCalledTimes(1);
            expect(nano.put.mock.calls[0][0]).toBe('');
            expect(nano.put.mock.calls[0][1]).toMatchSnapshot();
        });
    });
});
