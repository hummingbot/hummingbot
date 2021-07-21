'use strict';

var h = require('react').createElement;
var create = require('../index').create;
var addonCache = require('../addon/cache').addon;
var addonStable = require('../addon/stable').addon;
var addonNesting = require('../addon/nesting').addon;
var addonAtoms = require('../addon/atoms').addon;
var addonSnake = require('../addon/snake').addon;
var addonKeyframes = require('../addon/keyframes').addon;
var addonRule = require('../addon/rule').addon;
var addonSheet = require('../addon/sheet').addon;
var addonJsx = require('../addon/jsx').addon;
var addonStyle = require('../addon/style').addon;
var addonStyled = require('../addon/styled').addon;
var addonDecorator = require('../addon/decorator').addon;
var addonSourcemaps = require('../addon/sourcemaps').addon;

exports.preset = function (config) {
    config = config || {};
    config.h = config.h || h;

    var nano = create(config);

    addonCache(nano);
    addonStable(nano);
    addonNesting(nano);
    addonAtoms(nano);
    addonSnake(nano);
    addonKeyframes(nano);
    addonRule(nano);
    addonSheet(nano);
    addonJsx(nano);
    addonStyle(nano);
    addonStyled(nano);
    addonDecorator(nano);

    if (process.env.NODE_ENV !== 'production') {
        addonSourcemaps(nano);
    }

    return nano;
};
