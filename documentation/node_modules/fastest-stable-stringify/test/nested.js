'use strict';

var test = require('tape');
var stringify = require('../');

test('nested', function (t) {
    t.plan(1);
    var obj = { c: 8, b: [{z:6,y:5,x:4},7], a: 3 };
    t.equal(stringify(obj), '{"a":3,"b":[{"x":4,"y":5,"z":6},7],"c":8}');
});

test('repeated non-cyclic value', function(t) {
    t.plan(1);
    var one = { x: 1 };
    var two = { a: one, b: one };
    t.equal(stringify(two), '{"a":{"x":1},"b":{"x":1}}');
});

test('acyclic but with reused obj-property pointers', function (t) {
    t.plan(1);
    var x = { a: 1 };
    var y = { b: x, c: x };
    t.equal(stringify(y), '{"b":{"a":1},"c":{"a":1}}');
});
