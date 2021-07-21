'use strict';

var addonCssom = require('./cssom').addon;

exports.addon = function (renderer) {
    if (!renderer.putRule) {
        addonCssom(renderer);
    }

    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('pipe', renderer, ['createRule']);
    }

    var counter = 0;

    renderer.pipe = function () {
        var rules = {};
        var className = renderer.pfx + 'pipe-' + (counter++).toString(36);
        var attr = 'data-' + className;
        var scope1 = '.' + className;
        var scope2 = '[' + attr + ']';

        var obj = {
            attr: attr,
            className: className,
            css: function (css) {
                for (var selectorTemplate in css) {
                    var declarations = css[selectorTemplate];
                    var rule = rules[selectorTemplate];

                    if (!rule) {
                        var selector = selectorTemplate.replace('&', scope1) + ',' + selectorTemplate.replace('&', scope2);

                        rules[selectorTemplate] = rule = renderer.putRule(selector);
                    }

                    for (var prop in declarations)
                        rule.style.setProperty(prop, declarations[prop]);
                }

                // GC
                for (var selectorTemplate2 in rules) {
                    if (!(selectorTemplate2 in css)) {
                        rules[selectorTemplate2].remove();
                        delete rules[selectorTemplate2];
                    }
                }
            },
            remove: function () {
                for (var selectorTemplate in rules)
                    renderer.sh.deleteRule(rule.index);
            }
        };

        return obj;
    };
};
