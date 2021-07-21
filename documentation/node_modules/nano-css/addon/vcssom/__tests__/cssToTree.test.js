/* eslint-disable */
'use strict';

var cssToTree = require('../cssToTree').cssToTree;

describe('cssToTree', function () {
    test('exist', function () {
        expect(cssToTree).toBeInstanceOf(Function);
    });

    test('simple object', () => {
        var tree = {};
        cssToTree(tree, {color: 'red'}, '&', '');

        expect(tree).toEqual({
            '': {
                '&': {
                    color: 'red'
                }
            }
        });
    });

    test('multiple properties', () => {
        var tree = {};
        var css = {
            color: 'red',
            border: '1px solid tomato',
            textDecoration: 'underline,'
        };
        cssToTree(tree, css, '&', '');

        expect(tree).toEqual({ '':
        { '&':
           { color: 'red',
             border: '1px solid tomato',
             textDecoration: 'underline,' } } });
    });

    test('nested selector', () => {
        var tree = {};
        var css = {
            color: 'red',
            svg: {
                fill: 'green',
            }
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({
            '': {
                'X svg': {
                    fill: 'green'
                },
                X: {
                    color: 'red'
                }
            }
        });
    });

    test('nesting with single & pseudo selector', () => {
        var tree = {};
        var css = {
            svg: {
                fill: 'red',
            },
            '&:hover': {
                fill: 'green',
            }
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({"": {"X svg": {"fill": "red"}, "X:hover": {"fill": "green"}}});
    });

    test('more complicated nesting', () => {
        var tree = {};
        var css = {
            border: '1px solid red',
            fontFamily: 'monospace',
            '&:hover': {
                color: 'red',
            },
            '.global_class &': {
                textDecoration: 'underline',
            },
            '& svg': {
                fill: 'red',
            },
            '&:hover svg': {
                fill: 'green',
            }
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({ '':
        { X: { border: '1px solid red', fontFamily: 'monospace' },
          'X:hover': { color: 'red' },
          '.global_class X': { textDecoration: 'underline' },
          'X svg': { fill: 'red' },
          'X:hover svg': { fill: 'green' } } });
    });

    test('interpolates multiple ampersands', () => {
        var tree = {};
        var css = {
            '&:hover,&:active': {
                color: 'red',
            },
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({ '': { 'X:hover,X:active': { color: 'red' } } });
    });

    test('interpolates multiple ampersands wither further nesting', () => {
        var tree = {};
        var css = {
            '&:hover,&:active': {
                svg: {
                    fill: 'red',
                }
            },
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({ '': { 'X:hover svg,X:active svg': { fill: 'red' } } });
    });

    test('supports media query', () => {
        var tree = {};
        var css = {
            '@media screen': {
                color: 'red',
            }
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({ '@media screen': { X: { color: 'red' } } });
    });

    test('media query with other values', () => {
        var tree = {};
        var css = {
            color: 'green',
            '@media screen': {
                color: 'red',
                '&:hover': {
                    color: 'blue',
                }
            }
        };
        cssToTree(tree, css, 'X', '');

        expect(tree).toEqual({ '': { X: { color: 'green' } },
        '@media screen': { X: { color: 'red' }, 'X:hover': { color: 'blue' } } });
    });
});
