/* eslint-disable no-invalid-this */
'use strict';

// SEE TACHYONS REFERENCE: https://tachyons.io/#style

var addonSnake = require('./snake').addon;

var colors = {
    black: 'rgba(0,0,0,1)',
    black90: 'rgba(0,0,0,.9)',
    black80: 'rgba(0,0,0,.8)',
    black70: 'rgba(0,0,0,.7)',
    black60: 'rgba(0,0,0,.6)',
    black50: 'rgba(0,0,0,.5)',
    black40: 'rgba(0,0,0,.4)',
    black30: 'rgba(0,0,0,.3)',
    black20: 'rgba(0,0,0,.2)',
    black10: 'rgba(0,0,0,.1)',
    black05: 'rgba(0,0,0,.05)',
    black025: 'rgba(0,0,0,.025)',
    black0125: 'rgba(0,0,0,.0125)',
    nearBlack: '#111',
    darkGray: '#333',
    midGray: '#555',
    gray: '#777',
    white: 'rgba(255,255,255,1)',
    white90: 'rgba(255,255,255,.9)',
    white80: 'rgba(255,255,255,.8)',
    white70: 'rgba(255,255,255,.7)',
    white60: 'rgba(255,255,255,.6)',
    white50: 'rgba(255,255,255,.5)',
    white40: 'rgba(255,255,255,.4)',
    white30: 'rgba(255,255,255,.3)',
    white20: 'rgba(255,255,255,.2)',
    white10: 'rgba(255,255,255,.1)',
    white05: 'rgba(255,255,255,.05)',
    white025: 'rgba(255,255,255,.025)',
    white0125: 'rgba(255,255,255,.0125)',
    silver: '#999',
    lightSilver: '#aaa',
    lightGray: '#eee',
    nearWhite: '#f4f4f4',
    darkRed: '#e7040f',
    red: '#ff4136',
    lightRed: '#ff725c',
    orange: '#ff6300',
    gold: '#ffb700',
    yellow: '#ffde37',
    lightYellow: '#fbf1a9',
    purple: '#5e2ca5',
    lightPurple: '#a463f2',
    darkPink: '#d5008f',
    hotPink: '#ff41b4',
    pink: '#ff80cc',
    lightPink: '#ffa3d7',
    darkGreen: '#137752',
    green: '#19a974',
    lightGreen: '#9eebcf',
    navy: '#001b44',
    darkBlue: '#00449e',
    blue: '#357edd',
    lightBlue: '#96ccff',
    lightestBlue: '#cdecff',
    washedBlue: '#f6fffe',
    washedGreen: '#e8fdf5',
    washedYellow: '#fffceb',
    washedRed: '#ffdfdf',
};

var tachyons = [
    // Font sizes
    ['f1', 'fontSize', '3rem'],
    ['f2', 'fontSize', '2.25rem'],
    ['f3', 'fontSize', '1.5rem'],
    ['f4', 'fontSize', '1.25rem'],
    ['f5', 'fontSize', '1rem'],
    ['f6', 'fontSize', '.875rem'],

    // Text decorations
    ['strike', 'textDecoration', 'line-through'],
    ['ttc', 'textTransform', 'capitalize'],
    ['ttu', 'textTransform', 'uppercase'],

    // Fonts
    ['sans-serif', 'fontFamily', "-apple-system,BlinkMacSystemFont,'avenir next', avenir,helvetica,'helvetica neue',ubuntu,roboto,noto,'segoe ui',arial,sans-serif"],
    ['sansSerif', 'fontFamily', "-apple-system,BlinkMacSystemFont,'avenir next', avenir,helvetica,'helvetica neue',ubuntu,roboto,noto,'segoe ui',arial,sans-serif"],
    ['serif', 'fontFamily', 'georgia,times,serif'],
    ['code', 'fontFamily', 'Consolas,monaco,monospace'],
    ['courier', 'fontFamily', "'Courier Next', courier, monospace"],
    ['helvetica', 'fontFamily', "'helvetica neue', helvetica, sans-serif"],
    ['avenir', 'fontFamily', "'avenir next', avenir, sans-serif"],
    ['athelas', 'fontFamily', 'athelas, georgia, serif'],
    ['georgia', 'fontFamily', 'georgia, serif'],
    ['times', 'fontFamily', 'times, seriff'],
    ['bodoni', 'fontFamily', '"Calisto MT", serif'],
    ['calisto', 'fontFamily', '"Bodoni MT", serif'],
    ['garamond', 'fontFamily', 'garamond, serif'],
    ['baskerville', 'fontFamily', 'baskerville, serif'],

    // Measures
    ['measure-wide', 'maxWidth', '34em'],
    ['measureWide', 'maxWidth', '34em'],
    ['measure', 'maxWidth', '30em'],
    ['measure-narrow', 'maxWidth', '20em'],
    ['measureNarrow', 'maxWidth', '20em'],

    // Grid
    ['fl', 'float', 'left'],
    ['w100', 'width', '100%'],
    ['w90', 'width', '90%'],
    ['w80', 'width', '80%'],
    ['w75', 'width', '75%'],
    ['w70', 'width', '70%'],
    ['w60', 'width', '60%'],
    ['w50', 'width', '50%'],
    ['w40', 'width', '40%'],
    ['w30', 'width', '30%'],
    ['w25', 'width', '25%'],
    ['w20', 'width', '20%'],
    ['w10', 'width', '10%'],
    ['wThird', 'width', '33.33333%'],
    ['wTwoThirds', 'width', '36.66667%'],

    // Borders
    ['ba', 'border-style', 'solid', 'border-width', '1px'],
    ['bt', 'border-top-style', 'solid', 'border-top-width', '1px'],
    ['br', 'border-right-style', 'solid', 'border-right-width', '1px'],
    ['bb', 'border-bottom-style', 'solid', 'border-bottom-width', '1px'],
    ['bl', 'border-left-style', 'solid', 'border-left-width', '1px'],
    ['bn', 'border-style', 'none', 'border-width', 0],

    // Border styles
    ['bDotted', 'border-style', 'dotted'],
    ['bDashed', 'border-style', 'dashed'],
    ['bSolid', 'border-style', 'solid'],
    ['bNone', 'border-style', 'none'],

    // Border width
    ['bw0', 'borderWidth', 0],
    ['bw1', 'borderWidth', '.125rem'],
    ['bw2', 'borderWidth', '.25rem'],
    ['bw3', 'borderWidth', '.5rem'],
    ['bw4', 'borderWidth', '1rem'],
    ['bw5', 'borderWidth', '2rem'],

    // Border radii
    ['br0', 'borderRadius', 0],
    ['br1', 'borderRadius', '.125rem'],
    ['br2', 'borderRadius', '.25rem'],
    ['br3', 'borderRadius', '.5rem'],
    ['br4', 'borderRadius', '1rem'],
    ['br100', 'borderRadius', '100%'],
    ['brPill', 'borderRadius', '9999px'],
    ['brBottom', 'borderTopLeftRadius', 0, 'borderTopRightRadius', 0],
    ['brTop', 'borderBottomLeftRadius', 0, 'borderBottomRightRadius', 0],
    ['brRight', 'borderTopLeftRadius', 0, 'borderBottomLeftRadius', 0],
    ['brLeft', 'borderTopRightRadius', 0, 'borderBottomRightRadius', 0],
];

// Colors
for (var name in colors) {
    var capitalized = name[0].toUpperCase() + name.substr(1);
    var color = colors[name];

    // Colors
    tachyons.push([name, 'color', color]);

    // Background colors
    tachyons.push(['bg' + capitalized, 'backgroundColor', color]);

    // Border colors
    tachyons.push(['b' + capitalized, 'borderColor', color]);
}

exports.addon = function (renderer, ruleOverrides) {
    var rules = {};

    function onTachyon (tachyon) {
        rules[tachyon[0]] = function () {
            for (var i = 1; i < tachyon.length; i += 2) {
                this[tachyon[i]] = tachyon[i + 1];
            }
        };
    }

    for (var i = 0; i < tachyons.length; i++)
        onTachyon(tachyons[i]);

    // Add hover rules
    rules.grow = function () {
        this['-moz-osx-font-smoothing'] = 'grayscale';
        this.backfaceVisibility = 'hidden';
        this.transform = 'translateZ(0)';
        this.transition = 'transform 0.25s ease-out';
        this[':hover'] = {
            transform: 'scale(1.05)',
        };
        this[':focus'] = {
            transform: 'scale(1.05)',
        };
    };

    rules.dim = function () {
        this.opacity = 1;
        this.transition = 'opacity .15s ease-in';
        this[':hover'] = {
            opacity: '.5',
        };
        this[':focus'] = {
            opacity: '.5',
        };
    };

    addonSnake(renderer, renderer.assign(rules, ruleOverrides || {}));
};
