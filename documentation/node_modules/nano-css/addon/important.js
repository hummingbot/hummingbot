'use strict';

function hasImportant (rawDecl) {
    var parts = rawDecl.split(' ');

    for (var i = 0; i < parts.length; i++) {
        var part = parts[i].trim();

        if (part === '!important') return true;
    }

    return false;
}

exports.addon = function (renderer) {
    var decl = renderer.decl;

    renderer.decl = function (prop, value) {
        var rawDecl = decl(prop, value);
        var decls = rawDecl.split(';');
        var css = '';

        for (var i = 0; i < decls.length; i++) {
            rawDecl = decls[i].trim();

            if (!rawDecl) continue;

            // Don't add "!important" if it is already added.
            if (!hasImportant(rawDecl)) {
                css += rawDecl + ' !important;';
            } else {
                css += rawDecl + ';';
            }
        }

        return css;
    };
};
