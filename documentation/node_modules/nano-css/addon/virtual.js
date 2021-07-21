'use strict';

var createMemoizer = function (pfx) {
    var offset = 10;
    var msb = 35;
    var power = 1;

    var self = {
        cache: {},
        length: 0,

        next: function () {
            var vcount = self.length + offset;

            if (vcount === msb) {
                offset += (msb + 1) * 9;
                msb = Math.pow(36, ++power) - 1;
            }
            self.length++;

            return vcount;
        },

        get: function () {
            var curr = self.cache;
            var lastIndex = arguments.length - 1;
            var lastStep = arguments[lastIndex];

            for (var i = 0; i < lastIndex; i++) {
                var step = arguments[i] || '_';

                if (!curr[step]) curr[step] = {};
                curr = curr[step];
            }

            if (!curr[lastStep]) curr[lastStep] = pfx + self.next().toString(36);

            return curr[lastStep];
        }
    };

    return self;
};

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('virtual', renderer, ['rule', 'putRaw']);
    }

    renderer.memo = createMemoizer(renderer.pfx);

    renderer.atomic = function (selectorTemplate, rawDecl, atrule) {
        var memo = renderer.memo;
        var memoLength = memo.length;
        var className = memo.get(atrule, selectorTemplate, rawDecl);

        if (memoLength < memo.length) {
            var selector = selectorTemplate.replace(/&/g, '.' + className);
            var str = selector + '{' + rawDecl + '}';

            if (atrule) {
                str = atrule + '{' + str + '}';
            }

            renderer.putRaw(str);
        }

        return className;
    };

    renderer.virtual = function (selectorTemplate, decls, atrule) {
        selectorTemplate = selectorTemplate || '&';

        var classNames = '';

        for (var prop in decls) {
            var value = decls[prop];

            if (prop.indexOf('keyframes') > -1) {
                renderer.putAt('', value, prop);
                continue;
            }

            if ((value instanceof Object) && !(value instanceof Array)) {
                if (prop[0] === '@') {
                    classNames += renderer.virtual(selectorTemplate, value, prop);
                } else {
                    classNames += renderer.virtual(renderer.selector(selectorTemplate, prop), value, atrule);
                }
            } else {
                var rawDecl = renderer.decl(prop, value);
                var rawDecls = rawDecl.split(';');

                for (var i = 0; i < rawDecls.length; i++) {
                    var d = rawDecls[i];
                    if (d) classNames += ' ' + renderer.atomic(selectorTemplate, d, atrule);
                }
            }
        }

        return classNames;
    };

    renderer.rule = function (decls) {
        return renderer.virtual('&', decls);
    };
};
