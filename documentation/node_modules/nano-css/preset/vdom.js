'use strict';

var create = require('../index').create;
var addonCache = require('../addon/cache').addon;
var addonStable = require('../addon/stable').addon;
var addonNesting = require('../addon/nesting').addon;
var addonAtoms = require('../addon/atoms').addon;
var addonKeyframes = require('../addon/keyframes').addon;
var addonRule = require('../addon/rule').addon;
var addonSheet = require('../addon/sheet').addon;
var addonJsx = require('../addon/jsx').addon;
var addonSourcemaps = require('../addon/sourcemaps').addon;

exports.preset = function (config) {
    if (process.env.NODE_ENV !== 'production') {
        if (!config || !(config instanceof Object) || !config.h) {
            console.error(
                'For "vdom" nano-css preset you have to provide virtual DOM ' +
                'hyperscript function h. Such as: preset({h: require("react").createElement})'
            );
        }
    }

    var nano = create(config);

    addonCache(nano);
    addonStable(nano);
    addonNesting(nano);
    addonAtoms(nano);
    addonKeyframes(nano);
    addonRule(nano);
    addonSheet(nano);
    addonJsx(nano);

    if (process.env.NODE_ENV !== 'production') {
        addonSourcemaps(nano);
    }

    return nano;
};
