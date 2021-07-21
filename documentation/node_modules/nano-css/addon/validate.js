'use strict';

var csstree = require('css-tree');
var syntax = csstree.lexer;

function validate(css, filename) {
    var errors = [];
    var ast = csstree.parse(css, {
        filename: filename,
        positions: true,
        onParseError: function(error) {
            errors.push(error);
        }
    });

    csstree.walk(ast, {
        visit: 'Declaration',
        enter: function(node) {
            var match = syntax.matchDeclaration(node);
            var error = match.error;

            if (error) {
                var message = error.rawMessage || error.message || error;

                // ignore errors except those which make sense
                if (error.name !== 'SyntaxMatchError' &&
                    error.name !== 'SyntaxReferenceError') {
                    return;
                }

                if (message === 'Mismatch') {
                    message = 'Invalid value for `' + node.property + '`';
                } else if (message === 'Uncomplete match') {
                    message = 'The rest part of value can\'t be matched to `' + node.property + '` syntax';
                }

                errors.push({
                    name: error.name,
                    node: node,
                    loc: error.loc || node.loc,
                    line: error.line || node.loc && node.loc.start && node.loc.start.line,
                    column: error.column || node.loc && node.loc.start && node.loc.start.column,
                    property: node.property,
                    message: message,
                    error: error
                });
            }
        }
    });

    return errors;
}

exports.addon = function (renderer) {
    if (process.env.NODE_ENV !== 'production') {
        require('./__dev__/warnOnMissingDependencies')('validate', renderer, ['putRaw']);
    }

    if (process.env.NODE_ENV === 'production') {
        console.warn(
            'You are using nano-css "validate" in production. ' +
            'This addon is meant to be used only in development.'
        );
    }

    var putRaw = renderer.putRaw;

    renderer.putRaw = function (rawCssRule) {
        var errors = validate(rawCssRule);

        if (errors && errors.length) {
            errors.forEach(function (error) {
                console.error('nano-css error, ' + error.name + ': ' + error.message);
                // eslint-disable-next-line
                console.log(error);
                console.error(rawCssRule);
            });
        }

        return putRaw.apply(renderer, arguments);
    };
};
