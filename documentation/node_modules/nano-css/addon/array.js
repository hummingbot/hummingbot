'use strict';

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('rule', renderer, ['put', 'decl']);
    }

    var decl = renderer.decl;

    renderer.decl = function (prop, value) {
        var result = decl(prop, value);

        if (value instanceof Array) {
            var pos = result.indexOf(':');

            prop = result.substr(0, pos + 1);

            result = prop + value.join(';' + prop) + ';';
        }

        return result;
    };

    var put = renderer.put;

    renderer.put = function (selector, decls, atrule) {
        if (decls instanceof Array) {
            decls = renderer.assign.apply(null, decls);
        }

        return put(selector, decls, atrule);
    };
};
