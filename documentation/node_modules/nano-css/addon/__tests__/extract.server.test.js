/** @jest-environment node */
/* eslint-disable */
'use strict';

var create = require('../../index').create;
var addonRule = require('../../addon/rule').addon;
var addonCache = require('../../addon/cache').addon;
var addonSheet = require('../../addon/sheet').addon;
var addonJsx = require('../../addon/jsx').addon;
var addonStyle = require('../../addon/style').addon;
var addonStyled = require('../../addon/styled').addon;
var addonExtract = require('../../addon/extract').addon;

var createNano = function () {
    var nano = create({
        h: require('react').createElement
    });

    addonRule(nano);
    addonCache(nano);
    addonSheet(nano);
    addonJsx(nano);
    addonStyle(nano);
    addonStyled(nano);
    addonExtract(nano);

    return nano;
};

describe('extract', function () {
    it('extracts rule() CSS', function () {
        var nano = createNano();

        nano.rule({
            color: 'blue'
        });

        expect(nano.raw.includes('color:blue')).toBe(true);
    });

    it('extracts sheet() CSS', function () {
        var nano = createNano();

        nano.sheet({
            button: {
                color: 'pink'
            }
        });

        expect(nano.raw.includes('color:pink')).toBe(true);
    });

    it('extracts jsx() CSS', function (done) {
        var nano = createNano();

        var Button = nano.jsx('button', {
            cursor: 'pointer',
            background: 'blue'
        });

        process.nextTick(function () {
            expect(nano.raw.includes('cursor:pointer')).toBe(true);
            expect(nano.raw.includes('background:blue')).toBe(true);

            done();
        });
    });

    it('extracts style() CSS', function (done) {
        var nano = createNano();

        var Button = nano.style('button', {
            cursor: 'pointer',
            background: 'blue'
        });

        process.nextTick(function () {
            expect(nano.raw.includes('cursor:pointer')).toBe(true);
            expect(nano.raw.includes('background:blue')).toBe(true);

            done();
        });
    });

    it('extracts style() dynamic CSS', function (done) {
        var nano = createNano();

        var Button = nano.style('button', {
            cursor: 'pointer',
            background: 'red'
        }, function () {
            return {
                border: '1px solid red'
            };
        });

        process.nextTick(function () {
            expect(nano.raw.includes('cursor:pointer')).toBe(true);
            expect(nano.raw.includes('background:red')).toBe(true);
            expect(nano.raw.includes('border:1px solid red')).toBe(true);

            done();
        });
    });

    it('extracts style() dynamic CSS', function (done) {
        var nano = createNano();

        var Button = nano.style('button', {
            cursor: 'pointer',
            background: 'red'
        }, function (props) {
            return {
                border: '1px solid red',
                padding: props.big ? '20px' : '10px'
            };
        });

        Button.defaultProps = {
            big: true
        };

        process.nextTick(function () {
            expect(nano.raw.includes('cursor:pointer')).toBe(true);
            expect(nano.raw.includes('background:red')).toBe(true);
            expect(nano.raw.includes('border:1px solid red')).toBe(true);
            expect(nano.raw.includes('padding:20px')).toBe(true);

            done();
        });
    });

    it('extracts styled()() dynamic CSS', function (done) {
        var nano = createNano();

        var Button = nano.styled.button({
            cursor: 'pointer',
            background: 'red'
        }, function (props) {
            return {
                border: '1px solid red',
                padding: props.big ? '20px' : '10px'
            };
        });

        Button.defaultProps = {
            big: true
        };

        process.nextTick(function () {
            expect(nano.raw.includes('cursor:pointer')).toBe(true);
            expect(nano.raw.includes('background:red')).toBe(true);
            expect(nano.raw.includes('border:1px solid red')).toBe(true);
            expect(nano.raw.includes('padding:20px')).toBe(true);

            done();
        });
    });
});
