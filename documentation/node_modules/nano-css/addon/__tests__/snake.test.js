/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonCache = require('../../addon/cache').addon;
var addonSnake = require('../../addon/snake').addon;

function createNano (config) {
    var nano = create(config);

    addonRule(nano);
    addonCache(nano);
    addonSnake(nano);

    return nano;
};

describe('snake', function () {
    it('works', function () {
        var nano = createNano();

        expect(nano.s.bg('red').obj).toEqual({
            background: 'red'
        });
    });

    it('.rel', function () {
        var nano = createNano();

        expect(nano.s.rel.obj).toEqual({
            position: 'relative',
        });
    });

    it('.abs', function () {
        var nano = createNano();

        expect(nano.s.abs.obj).toEqual({
            position: 'absolute',
        });
    });

    it('.hover', function () {
        var nano = createNano();

        expect(nano.s.hover(nano.s.abs).obj).toEqual({
            ':hover': {
                position: 'absolute',
            }
        });
    });

    it('.focus', function () {
        var nano = createNano();

        expect(nano.s.focus(nano.s.abs).obj).toEqual({
            ':focus': {
                position: 'absolute',
            }
        });
    });

    describe('accents', function () {
        it('semantic', function () {
            var nano = createNano();

            expect(nano.s.bold.italic.underline.obj).toEqual({
                fontStyle: 'italic',
                fontWeight: 'bold',
                textDecoration: 'underline',
            });
        });

        it('shorhand', function () {
            var nano = createNano();

            expect(nano.s.b.i.u.obj).toEqual({
                fontStyle: 'italic',
                fontWeight: 'bold',
                textDecoration: 'underline',
            });
        });
    });

    describe('.s', function () {
        it('any value', function () {
            var nano = createNano();

            expect(nano.s.s('box-shadow', '0 0 3px black').obj).toEqual({
                'box-shadow': '0 0 3px black',
            });
        });

        it('nesting', function () {
            var nano = createNano();

            expect(nano.s.s(':hover', nano.s.u.obj).obj).toEqual({
                ':hover': {
                    textDecoration: 'underline'
                }
            });
        });

        it('nesting shorthand', function () {
            var nano = createNano();

            expect(nano.s.s(':hover', nano.s.u).obj).toEqual({
                ':hover': {
                    textDecoration: 'underline'
                }
            });
        });

        it('accepts an object', function () {
            var nano = createNano();

            expect(nano.s.s({color: 'red', font: 'Verdana'}).obj).toEqual({
                color: 'red',
                font: 'Verdana'
            });
        });
    });
});
